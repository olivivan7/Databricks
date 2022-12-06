# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC 
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px">
# MAGIC </div>

# COMMAND ----------

# MAGIC %md # Decision Trees
# MAGIC 
# MAGIC In the previous notebook, you were working with the parametric model, Linear Regression. We could do some more hyperparameter tuning with the linear regression model, but we're going to try tree based methods and see if our performance improves.
# MAGIC 
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) In this lesson you:<br>
# MAGIC  - Identify the differences between single node and distributed decision tree implementations
# MAGIC  - Get the feature importance
# MAGIC  - Examine common pitfalls of decision trees

# COMMAND ----------

# MAGIC %run "./Includes/Classroom-Setup"

# COMMAND ----------

file_path = f"{datasets_dir}/airbnb/sf-listings/sf-listings-2019-03-06-clean.delta/"
airbnb_df = spark.read.format("delta").load(file_path)
train_df, test_df = airbnb_df.randomSplit([.8, .2], seed=42)

# COMMAND ----------

# MAGIC %md ## How to Handle Categorical Features?
# MAGIC 
# MAGIC We saw in the previous notebook that we can use StringIndexer/OneHotEncoder/VectorAssembler or RFormula.
# MAGIC 
# MAGIC **However, for decision trees, and in particular, random forests, we should not OHE our variables.**
# MAGIC 
# MAGIC There is an excellent <a href="https://towardsdatascience.com/one-hot-encoding-is-making-your-tree-based-ensembles-worse-heres-why-d64b282b5769#:~:text=One%2Dhot%20encoding%20categorical%20variables,importance%20resulting%20in%20poorer%20performance" target="_blank">blog</a> on this, and the essence is:
# MAGIC >>> "One-hot encoding categorical variables with high cardinality can cause inefficiency in tree-based methods. Continuous variables will be given more importance than the dummy variables by the algorithm, which will obscure the order of feature importance and can result in poorer performance."

# COMMAND ----------

from pyspark.ml.feature import StringIndexer

categorical_cols = [field for (field, dataType) in train_df.dtypes if dataType == "string"]
index_output_cols = [x + "Index" for x in categorical_cols]

string_indexer = StringIndexer(inputCols=categorical_cols, outputCols=index_output_cols, handleInvalid="skip")

# COMMAND ----------

# MAGIC %md ## VectorAssembler
# MAGIC 
# MAGIC Let's use the <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.feature.VectorAssembler.html?highlight=vectorassembler#pyspark.ml.feature.VectorAssembler" target="_blank">VectorAssembler</a> to combine all of our categorical and numeric inputs.

# COMMAND ----------

from pyspark.ml.feature import VectorAssembler

# Filter for just numeric columns (and exclude price, our label)
numeric_cols = [field for (field, dataType) in train_df.dtypes if ((dataType == "double") & (field != "price"))]
# Combine output of StringIndexer defined above and numeric columns
assembler_inputs = index_output_cols + numeric_cols
vec_assembler = VectorAssembler(inputCols=assembler_inputs, outputCol="features")

# COMMAND ----------

# MAGIC %md ## Decision Tree
# MAGIC 
# MAGIC Now let's build a <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.regression.DecisionTreeRegressor.html?highlight=decisiontreeregressor#pyspark.ml.regression.DecisionTreeRegressor" target="_blank">DecisionTreeRegressor</a> with the default hyperparameters.

# COMMAND ----------

from pyspark.ml.regression import DecisionTreeRegressor

dt = DecisionTreeRegressor(labelCol="price")

# COMMAND ----------

# MAGIC %md ## Fit Pipeline
# MAGIC 
# MAGIC The following cell is expected to error, but we subsequently fix this.

# COMMAND ----------

from pyspark.ml import Pipeline

# Combine stages into pipeline
stages = [string_indexer, vec_assembler, dt]
pipeline = Pipeline(stages=stages)

# Uncomment to perform fit
# pipeline_model = pipeline.fit(train_df)

# COMMAND ----------

# MAGIC %md ## maxBins
# MAGIC 
# MAGIC What is this parameter <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.regression.DecisionTreeRegressor.html?highlight=decisiontreeregressor#pyspark.ml.regression.DecisionTreeRegressor.maxBins" target="_blank">maxBins</a>? Let's take a look at the PLANET implementation of distributed decision trees to help explain the **`maxBins`** parameter.

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC <img src="https://files.training.databricks.com/images/DistDecisionTrees.png" height=500px>

# COMMAND ----------

# MAGIC %md In Spark, data is partitioned by row. So when it needs to make a split, each worker has to compute summary statistics for every feature for  each split point. Then these summary statistics have to be aggregated (via tree reduce) for a split to be made. 
# MAGIC 
# MAGIC Think about it: What if worker 1 had the value **`32`** but none of the others had it. How could you communicate how good of a split that would be? So, Spark has a maxBins parameter for discretizing continuous variables into buckets, but the number of buckets has to be as large as the categorical variable with the highest cardinality.

# COMMAND ----------

# MAGIC %md Let's go ahead and increase maxBins to **`40`**.

# COMMAND ----------

dt.setMaxBins(40)

# COMMAND ----------

# MAGIC %md Take two.

# COMMAND ----------

pipeline_model = pipeline.fit(train_df)

# COMMAND ----------

# MAGIC %md ## Feature Importance
# MAGIC 
# MAGIC Let's go ahead and get the fitted decision tree model, and look at the feature importance scores.

# COMMAND ----------

dt_model = pipeline_model.stages[-1]
display(dt_model)

# COMMAND ----------

dt_model.featureImportances

# COMMAND ----------

# MAGIC %md ## Interpreting Feature Importance
# MAGIC 
# MAGIC Hmmm... it's a little hard to know what feature 4 vs 11 is. Given that the feature importance scores are "small data", let's use Pandas to help us recover the original column names.

# COMMAND ----------

import pandas as pd

features_df = pd.DataFrame(list(zip(vec_assembler.getInputCols(), dt_model.featureImportances)), columns=["feature", "importance"])
features_df

# COMMAND ----------

# MAGIC %md ## Why so few features are non-zero?
# MAGIC 
# MAGIC With SparkML, the default **`maxDepth`** is 5, so there are only a few features we could consider (we can also split on the same feature many times at different split points).
# MAGIC 
# MAGIC Let's use a Databricks widget to get the top-K features.

# COMMAND ----------

dbutils.widgets.text("top_k", "5")
top_k = int(dbutils.widgets.get("top_k"))

top_features = features_df.sort_values(["importance"], ascending=False)[:top_k]["feature"].values
print(top_features)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scale Invariant
# MAGIC 
# MAGIC With decision trees, the scale of the features does not matter. For example, it will split 1/3 of the data if that split point is 100 or if it is normalized to be .33. The only thing that matters is how many data points fall left and right of that split point - not the absolute value of the split point.
# MAGIC 
# MAGIC This is not true for linear regression, and the default in Spark is to standardize first. Think about it: If you measure shoe sizes in American vs European sizing, the corresponding weight of those features will be very different even those those measures represent the same thing: the size of a person's foot!

# COMMAND ----------

# MAGIC %md
# MAGIC ## Apply model to test set

# COMMAND ----------

pred_df = pipeline_model.transform(test_df)

display(pred_df.select("features", "price", "prediction").orderBy("price", ascending=False))

# COMMAND ----------

# MAGIC %md ## Pitfall
# MAGIC 
# MAGIC What if we get a massive Airbnb rental? It was 20 bedrooms and 20 bathrooms. What will a decision tree predict?
# MAGIC 
# MAGIC It turns out decision trees cannot predict any values larger than they were trained on. The max value in our training set was $10,000, so we can't predict any values larger than that.

# COMMAND ----------

from pyspark.ml.evaluation import RegressionEvaluator

regression_evaluator = RegressionEvaluator(predictionCol="prediction", labelCol="price", metricName="rmse")

rmse = regression_evaluator.evaluate(pred_df)
r2 = regression_evaluator.setMetricName("r2").evaluate(pred_df)
print(f"RMSE is {rmse}")
print(f"R2 is {r2}")

# COMMAND ----------

# MAGIC %md ## Uh oh!
# MAGIC 
# MAGIC This model is way worse than the linear regression model, and it's even worse than just predicting the average value.
# MAGIC 
# MAGIC In the next few notebooks, let's look at hyperparameter tuning and ensemble models to improve upon the performance of our single decision tree.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC &copy; 2022 Databricks, Inc. All rights reserved.<br/>
# MAGIC Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="https://www.apache.org/">Apache Software Foundation</a>.<br/>
# MAGIC <br/>
# MAGIC <a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="https://help.databricks.com/">Support</a>
